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

/**
 * Persona codes — mirrors `PersonaId` in `lib/cfo/hooks.ts` (canonical
 * 8-code set, services/profile/persona_analytics.PERSONA_CODES). Declared
 * locally so this data module stays dependency-free for the landing teaser.
 */
export type PersonaCode =
  | "growth"
  | "value"
  | "balanced"
  | "income"
  | "quant"
  | "speculator"
  | "daytrader"
  | "beginner";

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

/**
 * Persona-aware question hints (2026-06-10, record-as-spine memo §7 — CEO GO).
 *
 * The SEVEN QUESTIONS THEMSELVES NEVER VARY — one SoT, identical for every
 * user and for the landing teaser. What varies is a single optional hint
 * line rendered under a question, in the user's investor-persona register:
 * Beginner gets gentler, explanatory 존댓말; Quant gets terse formula
 * prompts; Value/Income get patience/cash-flow lenses; Growth gets
 * conviction-testing. `balanced` (and the FE-unexposed speculator/daytrader)
 * intentionally have NO entries — neutral fallback is the original copy.
 * Hints are Korean-only, matching the existing in-product helper register
 * (e.g. the answer placeholder).
 *
 * Consumed only by the in-product QuestionsStep (persona comes from the
 * `usePersona()` localStorage cache via `cachedPersonaId()` — never from a
 * fetch in the deposition flow). The landing teaser does not render hints.
 *
 * 법적 가드 (§17): every hint is the user interrogating their OWN decision —
 * no direction, no target, no 추천/조언, no BUY/SELL labels. A hint may
 * *describe* an act but never *direct* one.
 */
export const PERSONA_QUESTION_HINTS: Partial<
  Record<PersonaCode, Readonly<Record<number, string>>>
> = {
  beginner: {
    1: "어렵게 쓰지 않아도 됩니다 — 친구에게 말하듯 '왜 지금 이 종목인가' 한 줄이면 충분해요.",
    2: "손절선이 처음이라면: '여기까지 오면 내 생각이 틀렸다'고 인정할 가격 하나를 정해보세요.",
    6: "그 금액이 무겁게 느껴진다면, 그것도 중요한 답입니다. 잃어도 잠들 수 있는 크기인가요?",
  },
  quant: {
    2: "구조 레벨인가? (직전 저점·갭 등) Y/N + 가격.",
    3: "(목표 − 현재) ÷ (현재 − 손절) = ? 숫자로.",
    6: "최대 손실 = 수량 × (현재 − 손절). 원화로.",
  },
  value: {
    1: "가격에 대한 베팅인가, 기업에 대한 판단인가?",
    3: "논지가 1년을 견딘다면, 오늘 하루의 등락은 얼마나 중요한가?",
    7: "'싸 보여서' 들어갔던 지난번 — 인내가 보상받았나, 가치 함정이었나?",
  },
  income: {
    1: "목적이 시세 차익인가, 현금흐름인가? 둘이 섞이면 정리 기준도 흐려진다.",
    3: "배당·이자를 포함해도 이 계산이 성립하는가?",
    4: "높은 수익률(yield)에 끌린 것인가, 그 지속 가능성을 본 것인가?",
  },
  growth: {
    1: "모두가 아는 성장 스토리는 이미 가격에 있다. '아직' 반영되지 않은 게 뭔가?",
    4: "이 흥분은 논지에서 오나, 오르는 차트에서 오나?",
    6: "확신이 클수록 크기를 키우고 싶어진다 — 그 확신, 무엇으로 검증했나?",
  },
} as const;
