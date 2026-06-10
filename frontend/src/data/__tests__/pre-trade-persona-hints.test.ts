/**
 * Guards for PERSONA_QUESTION_HINTS (record-as-spine §7, 2026-06-10).
 *
 * The hints are persona-toned helper lines under the 7 deposition
 * questions. Two contracts locked here:
 *   1. Legal (§17 투자권유 금지): hints are self-interrogation only —
 *      no 추천/조언, no BUY/SELL labels, no imperative buy/sell Korean.
 *   2. Structural: hint keys must reference real question numbers and
 *      valid persona codes; `balanced` must stay EMPTY (it is the neutral
 *      fallback — giving it hints would silently change the default copy).
 */
import { describe, expect, it } from "vitest";
import {
  PRE_TRADE_QUESTIONS,
  PERSONA_QUESTION_HINTS,
  type PersonaCode,
} from "@/data/pre-trade-questions";

const VALID_CODES: readonly PersonaCode[] = [
  "growth", "value", "balanced", "income",
  "quant", "speculator", "daytrader", "beginner",
];

const QUESTION_NUMBERS = new Set(PRE_TRADE_QUESTIONS.map((q) => q.n));

// 추천/조언 (advice language), BUY/SELL labels, and imperative Korean
// buy/sell commands are banned. Descriptive nouns (매수/매도 as a thing
// that exists) are allowed — the landing hero itself says "매수·매도 직전".
const BANNED = [
  /추천/, /조언/,
  /\bBUY\b/, /\bSELL\b/,
  /사세요/, /파세요/, /사라[.!\s]/, /팔아라/,
  /매수하(세요|라)/, /매도하(세요|라)/,
];

describe("PERSONA_QUESTION_HINTS — structure", () => {
  it("every persona key is a valid code and every hint maps to a real question", () => {
    for (const [code, hints] of Object.entries(PERSONA_QUESTION_HINTS)) {
      expect(VALID_CODES).toContain(code as PersonaCode);
      for (const [n, text] of Object.entries(hints!)) {
        expect(QUESTION_NUMBERS.has(Number(n))).toBe(true);
        expect(typeof text).toBe("string");
        expect((text as string).trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("balanced stays empty — it IS the neutral fallback", () => {
    expect(PERSONA_QUESTION_HINTS.balanced).toBeUndefined();
  });

  it("speculator / daytrader have no hints (FE-unexposed, absorbed into neutral)", () => {
    expect(PERSONA_QUESTION_HINTS.speculator).toBeUndefined();
    expect(PERSONA_QUESTION_HINTS.daytrader).toBeUndefined();
  });
});

describe("PERSONA_QUESTION_HINTS — §17 legal copy guard", () => {
  it("no hint contains advice language or BUY/SELL labels", () => {
    for (const [code, hints] of Object.entries(PERSONA_QUESTION_HINTS)) {
      for (const [n, text] of Object.entries(hints!)) {
        for (const re of BANNED) {
          expect(
            re.test(text as string),
            `${code} Q${n} hint matches banned pattern ${re}: "${text}"`,
          ).toBe(false);
        }
      }
    }
  });

  it("the seven questions themselves also stay §17-clean", () => {
    for (const q of PRE_TRADE_QUESTIONS) {
      for (const re of BANNED) {
        expect(re.test(q.ko), `Q${q.n} ko matches ${re}`).toBe(false);
        expect(re.test(q.en), `Q${q.n} en matches ${re}`).toBe(false);
      }
    }
  });
});
