/**
 * /pre-trade phone flow as one line of steps, for the back gesture
 * (lib/use-history-steps):
 *
 *   0          setup (ticker · direction · reason)
 *   1 … 7      question 1 … 7
 *   8          review (the start button)
 *   null       cooldown / finished — the reflection has been started, so the
 *              flow is locked and back leaves the page
 *
 * The gates are the same ones the buttons and swipes already apply: the
 * questions open only from a complete setup, and a question opens only once
 * every question before it was acknowledged ("검토했음"). A history move
 * never acknowledges anything.
 */

import { PRE_TRADE_QUESTIONS } from "@/data/pre-trade-questions";

export type PreTradePhase = "setup" | "questions" | "cooldown" | "terminal";

/** Linear step for the phase + question cursor, or null once started. */
export function preTradeLinearStep(phase: PreTradePhase, questionCursor: number): number | null {
  if (phase === "setup") return 0;
  if (phase === "questions") return 1 + questionCursor;
  return null;
}

/** May the flow be at `step` given what the user has filled in? */
export function preTradeStepAllowed(
  step: number,
  { setupOk, acks }: { setupOk: boolean; acks: Record<number, boolean> },
): boolean {
  if (step <= 0) return true;
  if (!setupOk) return false;
  const questionsBefore = Math.min(step - 1, PRE_TRADE_QUESTIONS.length);
  for (let i = 0; i < questionsBefore; i++) {
    if (!acks[PRE_TRADE_QUESTIONS[i].n]) return false;
  }
  return step <= PRE_TRADE_QUESTIONS.length + 1;
}
