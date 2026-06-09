/**
 * Pre-Trade Checklist — the canonical seven reflective questions.
 *
 * SINGLE SOURCE OF TRUTH. Both the in-product reflection cycle
 * (`components/pre-trade/pre-trade-friction-core.tsx`, re-exported there as
 * `QUESTIONS`) and the landing marketing teaser
 * (`components/landing/deposition-teaser.tsx`) import from here — so the copy
 * a prospect reads on the landing page and the copy a user answers in-product
 * can never drift apart again.
 *
 * ── Why this feature exists (evidence) ───────────────────────────────────
 * Barber & Odean, "Trading Is Hazardous to Your Wealth" (Journal of Finance,
 * 2000): the households that traded most earned 11.4%/yr vs the market's
 * 17.9% — overtrading, driven by overconfidence, is what destroys retail
 * returns. The job of these seven questions is to add deliberate friction at
 * the one moment that matters: just before an entry.
 *
 * ── Why these seven (each question traces to a source) ───────────────────
 *   1. Thesis / edge        — Mark Douglas, *Trading in the Zone* ("define
 *                             your edge"; no edge = gambling). Edgewonk setup
 *                             confirmation.
 *   2. Stop / invalidation  — Steenbarger ("what tells you you're wrong, and
 *                             how will you recognize it?"). Edgewonk: stop at
 *                             a STRUCTURAL level (below a swing low), never an
 *                             arbitrary round number.
 *   3. Reward vs risk       — Edgewonk / standard desk practice: target ≥ 2×
 *                             the distance to stop (R:R ≥ 1:2).
 *   4. Emotional charge     — Steenbarger's pre-trade exercise: rate your
 *                             emotional state 1–10; above ~7, step away.
 *   5. Tilt / revenge check — The canonical revenge-trading diagnostic:
 *                             "Would I take this trade if my last one had been
 *                             a winner?" Surgically isolates tilt.
 *   6. Size + accepted loss — Douglas: ACCEPT the loss, in cash, BEFORE the
 *                             trade. Duke's premortem (imagine it has already
 *                             failed). Revenge check #3: "am I sizing normally?"
 *   7. Plan fit + record    — Revenge check #1 ("is this setup in my plan?") +
 *                             FOMO antidote (pre-defined criteria) + the app's
 *                             own "거울 / compounding memory": how did the last
 *                             one like this end?
 *
 * Design intent (anti-impulse, not trade-optimization): three of the seven now
 * demand a NUMBER (stop price, target/R:R, max loss in cash) and two probe
 * emotional state (charge gauge, tilt check). No internal jargon — the old
 * "persona allocation" / "drift band" wording is gone, replaced by plain
 * "the plan you wrote".
 *
 * Tone (2026-06-09): the substance above is unchanged, but the register was
 * calibrated to fit the full persona spread (Beginner → Quant, see
 * persona-showcase.tsx). The deposition's terse 반말 brand voice is kept, but
 * the accusatory/dismissive edges were softened (e.g. "당신은 틀린 것인가" →
 * "이 생각이 틀린 건가"; "그냥 찍은 숫자" → "그냥 정한 숫자"; commands like
 * "말해보라/상상하라" → "적어보라/그려보라", which also leans into the
 * journaling theme). A TRUE per-persona tone (Beginner gets gentler/explanatory
 * copy, Quant gets terse/numeric) would need persona wired into the pre-trade
 * flow — that is a reviewed change, proposed in docs/strategy, not done here.
 *
 * Legal posture (자본시장법 §17 투자권유 금지): every question is the USER
 * interrogating their OWN decision — never us advising a direction, a price,
 * or a target. Keep all edits in the second person, reflection-only. No
 * 추천/조언/recommend/advice, no BUY/SELL labels.
 */

export interface PreTradeQuestion {
  readonly n: number;
  readonly en: string;
  readonly ko: string;
}

export const PRE_TRADE_QUESTIONS: readonly PreTradeQuestion[] = [
  {
    n: 1,
    en: "Write your reason in one sentence — what did you see that others missed?",
    ko: "한 문장으로 진입 이유를 적어보라 — 남들이 놓친 무엇을 당신은 봤나?",
  },
  {
    n: 2,
    en: "How far down before this idea is wrong? Is that line one the chart supports — or just a number you picked?",
    ko: "어디까지 내려가면 이 생각이 틀린 건가? 그 선은 차트가 받쳐주는 자리인가, 그냥 정한 숫자인가?",
  },
  {
    n: 3,
    en: "Where's your target? Is it at least 2× the distance to your stop?",
    ko: "목표가는 어디까지 보나? 손절까지의 거리 대비 적어도 2배인가?",
  },
  {
    n: 4,
    en: "How worked up are you right now, 1–10? Over 7 — is this really the moment?",
    ko: "지금 얼마나 들떠 있나, 1–10 중? 7을 넘으면 — 지금이 정말 그 때인가?",
  },
  {
    n: 5,
    en: "If your last trade had been a winner, would you still take this one?",
    ko: "직전 거래가 만약 수익이었어도, 지금 이걸 똑같이 들어갔을까?",
  },
  {
    n: 6,
    en: "Is this your usual size? Picture the stop getting hit tomorrow — could you accept that loss right now?",
    ko: "평소 크기인가? 내일 손절에 닿는 장면을 그려보라 — 그 손실 금액을, 지금, 받아들일 수 있나?",
  },
  {
    n: 7,
    en: "Was this in your plan to begin with — or an exception you're making now? And last time you entered one like it, how did it end?",
    ko: "이건 원래 계획에 있던 자리인가, 지금 만드는 예외인가? 지난번 비슷한 진입은 어떻게 끝났나?",
  },
] as const;
