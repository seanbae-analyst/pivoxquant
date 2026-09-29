/**
 * PersonaEvolution carries no declared-vs-observed verdict — 2026-09-29.
 *
 * Its "Material drift" badge fired on `drift > 20 && declared ≠ observed`,
 * where `drift` was |declared score − observed score| and the declared score
 * was `25 + risk_tolerance*7` — a third definition of declared-vs-observed
 * next to the canonical one on /mirror (declared_vector_json, 9 axes). The
 * backend no longer sends `drift` or `declared.score`; this pins that a
 * stale cached payload that still has them cannot bring the badge back.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/cfo/hooks", async (orig) => {
  const actual = await orig<typeof import("@/lib/cfo/hooks")>();
  return {
    ...actual,
    usePersona: () => ({
      isLoading: false,
      // A pre-2026-09-29 cached payload: declared score + large drift, and
      // declared ≠ observed bucket.
      data: {
        declared: { persona: "income", label: "수익형", tagline: "x", score: 95 },
        observed: {
          window_30d: { date: "2026-09-01", persona: "daytrader", score: 60 },
          window_60d: { date: "2026-08-01", persona: "daytrader", score: 60 },
          window_90d: { date: "2026-07-01", persona: "daytrader", score: 60 },
        },
        sparkline: [
          { week: "2026-08-04", score: 60 },
          { week: "2026-08-11", score: 61 },
          { week: "2026-08-18", score: 60 },
        ],
        last_computed_at: null,
        drift: 80,
      },
    }),
    usePulse: () => ({ data: { history: [] } }),
  };
});

import { PersonaEvolution } from "@/components/dashboard/persona-evolution";

describe("PersonaEvolution — no declared-vs-observed drift verdict", () => {
  it("never renders the Material drift badge", () => {
    render(<PersonaEvolution bare />);
    expect(screen.queryByText(/material drift/i)).toBeNull();
  });

  it("does not flag the latest week for declared ≠ observed", () => {
    render(<PersonaEvolution bare />);
    // Flat series (60/61/60): nothing deviates from the median, so the only
    // way a week gets flagged is the removed declared-vs-observed clause.
    const last = screen.getByRole("button", { name: /Week of 2026-08-18/ });
    expect(last).toBeTruthy();
    expect(document.querySelectorAll('circle[r="7"]').length).toBe(0);
  });
});
