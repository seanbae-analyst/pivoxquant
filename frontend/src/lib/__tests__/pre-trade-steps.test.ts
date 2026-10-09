import { describe, it, expect } from "vitest";
import { preTradeLinearStep, preTradeStepAllowed } from "@/lib/pre-trade-steps";
import { PRE_TRADE_QUESTIONS } from "@/data/pre-trade-questions";

const allAcked = Object.fromEntries(PRE_TRADE_QUESTIONS.map((q) => [q.n, true]));

describe("preTradeLinearStep", () => {
  it("setup 0, question i → 1+i, locked once started", () => {
    expect(preTradeLinearStep("setup", 3)).toBe(0);
    expect(preTradeLinearStep("questions", 0)).toBe(1);
    expect(preTradeLinearStep("questions", PRE_TRADE_QUESTIONS.length)).toBe(8);
    expect(preTradeLinearStep("cooldown", 0)).toBeNull();
    expect(preTradeLinearStep("terminal", 0)).toBeNull();
  });
});

describe("preTradeStepAllowed", () => {
  it("setup is always reachable", () => {
    expect(preTradeStepAllowed(0, { setupOk: false, acks: {} })).toBe(true);
  });
  it("questions need a complete setup", () => {
    expect(preTradeStepAllowed(1, { setupOk: false, acks: {} })).toBe(false);
    expect(preTradeStepAllowed(1, { setupOk: true, acks: {} })).toBe(true);
  });
  it("a question needs every question before it acknowledged", () => {
    const q1 = PRE_TRADE_QUESTIONS[0].n;
    expect(preTradeStepAllowed(2, { setupOk: true, acks: {} })).toBe(false);
    expect(preTradeStepAllowed(2, { setupOk: true, acks: { [q1]: true } })).toBe(true);
    expect(preTradeStepAllowed(8, { setupOk: true, acks: { [q1]: true } })).toBe(false);
    expect(preTradeStepAllowed(8, { setupOk: true, acks: allAcked })).toBe(true);
  });
  it("nothing past the review screen", () => {
    expect(preTradeStepAllowed(9, { setupOk: true, acks: allAcked })).toBe(false);
  });
});
