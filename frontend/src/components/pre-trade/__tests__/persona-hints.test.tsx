/**
 * QuestionsStep persona-hint wiring (record-as-spine §7, 2026-06-10).
 *
 * Persona is resolved synchronously from the localStorage cache that
 * `usePersona()` maintains (`pq_cfo_persona_v1`) — the deposition flow
 * itself must NEVER issue a network request: the host modals' tests
 * assert strict apiFetch call counts. Contracts:
 *   - warm cache + real payload → that persona's hints render
 *   - `_isMock` payload → NO hints (the offline mock is always "growth";
 *     personalizing from it would be wrong for most users)
 *   - cold cache → NO hints (neutral copy, exactly the pre-wiring render)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useState } from "react";

// friction-core imports the api layer at module scope (for the cycle hook);
// mock it so this test can never touch the network.
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
  return { apiFetch: vi.fn(), ApiError };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { apiFetch } from "@/lib/api";
import { QuestionsStep } from "@/components/pre-trade/pre-trade-friction-core";
import { PERSONA_QUESTION_HINTS } from "@/data/pre-trade-questions";

const LS_PERSONA_KEY = "pq_cfo_persona_v1";

function seedPersona(persona: string, isMock = false) {
  window.localStorage.setItem(
    LS_PERSONA_KEY,
    JSON.stringify({
      declared: { persona, label: "x", tagline: "x", score: 80 },
      observed: {},
      sparkline: [],
      last_computed_at: null,
      drift: 0,
      ...(isMock ? { _isMock: true } : {}),
    }),
  );
}

function Harness() {
  const [acks, setAcks] = useState<Record<number, boolean>>({});
  const [answers, setAnswers] = useState<Record<number, string>>({});
  return (
    <QuestionsStep
      acks={acks}
      setAcks={setAcks}
      answers={answers}
      setAnswers={setAnswers}
      allAcked={false}
      submitting={false}
      onStart={() => {}}
      bare
    />
  );
}

describe("QuestionsStep — persona hints from the localStorage cache", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(apiFetch).mockReset();
  });

  it("renders the beginner hints when the cache holds a real beginner payload", async () => {
    seedPersona("beginner");
    render(<Harness />);
    const hint = await screen.findByTestId("persona-hint-1");
    expect(hint.textContent).toBe(PERSONA_QUESTION_HINTS.beginner![1]);
    expect(screen.getByTestId("persona-hint-2")).toBeTruthy();
    // beginner has no Q3 hint — only its own question numbers render.
    expect(screen.queryByTestId("persona-hint-3")).toBeNull();
  });

  it("renders NO hints for a balanced persona (neutral fallback)", () => {
    seedPersona("balanced");
    render(<Harness />);
    for (let n = 1; n <= 7; n++) {
      expect(screen.queryByTestId(`persona-hint-${n}`)).toBeNull();
    }
  });

  it("renders NO hints when the cached payload is the offline mock", () => {
    seedPersona("growth", /* isMock */ true);
    render(<Harness />);
    expect(screen.queryByTestId("persona-hint-1")).toBeNull();
    expect(screen.queryByTestId("persona-hint-4")).toBeNull();
  });

  it("renders NO hints on a cold cache, and never issues a fetch", () => {
    render(<Harness />);
    for (let n = 1; n <= 7; n++) {
      expect(screen.queryByTestId(`persona-hint-${n}`)).toBeNull();
    }
    expect(apiFetch).not.toHaveBeenCalled();
  });
});
